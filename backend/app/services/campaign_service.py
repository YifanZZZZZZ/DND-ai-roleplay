from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.api.schemas.campaigns import (
    CampaignCreate,
    CampaignMemberAdd,
    CampaignMembershipUpdate,
    CampaignUpdate,
    HpUpdate,
    SessionCreate,
)
from backend.app.core.errors import AppError, ConflictError, NotFoundError
from backend.app.db.models import (
    Campaign,
    CampaignMembership,
    Character,
    CharacterMemory,
    CharacterProfile,
    GameSession,
    Message,
    SessionCharacterState,
    SessionRuntime,
)
from backend.app.domain.enums import (
    CampaignLifecycleStatus,
    MemoryOrigin,
    ProfileStatus,
    RuntimeStatus,
    SessionStatus,
    UpdatedBy,
)
from backend.app.services.summary_service import SummaryService


class CampaignService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _detail_query(self):
        return select(Campaign).options(
            selectinload(Campaign.memberships).selectinload(CampaignMembership.character),
            selectinload(Campaign.sessions)
            .selectinload(GameSession.character_states)
            .selectinload(SessionCharacterState.character),
            selectinload(Campaign.sessions).selectinload(GameSession.runtime),
        )

    async def list(self) -> list[Campaign]:
        result = await self.session.scalars(
            self._detail_query().order_by(Campaign.created_at.desc())
        )
        return list(result)

    async def get(self, campaign_id: str) -> Campaign:
        campaign = await self.session.scalar(self._detail_query().where(Campaign.id == campaign_id))
        if campaign is None:
            raise NotFoundError("Campaign", campaign_id)
        return campaign

    async def _load_characters(self, character_ids: list[str]) -> list[Character]:
        unique_ids = list(dict.fromkeys(character_ids))
        if len(unique_ids) != len(character_ids):
            raise AppError("DUPLICATE_CHARACTER", "阵容中不能重复选择同一个角色。")
        result = await self.session.scalars(select(Character).where(Character.id.in_(unique_ids)))
        characters = list(result)
        if len(characters) != len(unique_ids):
            raise AppError("CHARACTER_NOT_FOUND", "阵容中包含不存在的角色。", status_code=404)
        normalized_names = [character.name.strip().casefold() for character in characters]
        if len(set(normalized_names)) != len(normalized_names):
            raise AppError("DUPLICATE_CHARACTER_NAME", "同一战役中的角色名称不能重复。")
        return characters

    async def create(self, payload: CampaignCreate) -> Campaign:
        characters = await self._load_characters(payload.character_ids)
        campaign = Campaign(
            name=payload.name.strip(),
            description=payload.description,
            dm_guide=payload.dm_guide,
            scene_notes=payload.scene_notes,
            module_content=payload.module_content,
            style_instructions=payload.style_instructions,
            opening_instructions=payload.opening_instructions,
        )
        campaign.memberships = [CampaignMembership(character=character) for character in characters]
        self.session.add(campaign)
        await self.session.commit()
        return await self.get(campaign.id)

    async def update(self, campaign_id: str, payload: CampaignUpdate) -> Campaign:
        campaign = await self.get(campaign_id)
        self._check_revision(campaign, payload.revision)
        if campaign.lifecycle_status != CampaignLifecycleStatus.PREPARATION and (
            payload.name is not None or payload.description is not None
        ):
            raise ConflictError("CAMPAIGN_NOT_EDITABLE", "只有筹备中的战役可以编辑基本信息。")
        if payload.name is not None:
            campaign.name = payload.name.strip()
        if payload.description is not None:
            campaign.description = payload.description
        if payload.dm_guide is not None:
            campaign.dm_guide = payload.dm_guide
        if payload.scene_notes is not None:
            campaign.scene_notes = payload.scene_notes
        if payload.module_content is not None:
            campaign.module_content = payload.module_content
        if payload.style_instructions is not None:
            campaign.style_instructions = payload.style_instructions
        if payload.opening_instructions is not None:
            campaign.opening_instructions = payload.opening_instructions
        if payload.play_mode is not None:
            campaign.play_mode = payload.play_mode
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def replace_memberships(
        self, campaign_id: str, payload: CampaignMembershipUpdate
    ) -> Campaign:
        campaign = await self.get(campaign_id)
        self._check_revision(campaign, payload.revision)
        if campaign.lifecycle_status != CampaignLifecycleStatus.PREPARATION:
            raise ConflictError("CAMPAIGN_ROSTER_LOCKED", "战役启动后不能用筹备接口替换整个阵容。")
        characters = await self._load_characters(payload.character_ids)
        campaign.memberships.clear()
        campaign.memberships.extend(
            CampaignMembership(character=character) for character in characters
        )
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def activate(self, campaign_id: str) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.lifecycle_status != CampaignLifecycleStatus.PREPARATION:
            raise ConflictError("CAMPAIGN_NOT_PREPARATION", "只有筹备中的战役可以启动。")
        if campaign.archived_at is not None:
            raise ConflictError("CAMPAIGN_ARCHIVED", "请先恢复归档的战役。")
        if not 1 <= len(campaign.memberships) <= 6:
            raise AppError("INVALID_ROSTER_SIZE", "启动战役需要选择 1 至 6 名角色。")
        incomplete = [
            membership.character.name
            for membership in campaign.memberships
            if not membership.character.roleplay_prompt.strip()
            or membership.character.active_sheet_version_id is None
        ]
        if incomplete:
            raise AppError(
                "CHARACTER_CONFIGURATION_INCOMPLETE",
                "所有角色必须配置 Roleplay Prompt 并激活有效角色卡后才能启动。",
                details={"characters": incomplete},
            )
        existing_active = await self.session.scalar(
            select(Campaign.id).where(Campaign.lifecycle_status == CampaignLifecycleStatus.ACTIVE)
        )
        if existing_active is not None:
            raise ConflictError("ACTIVE_CAMPAIGN_EXISTS", "当前已有一个正在进行的战役。")
        campaign.lifecycle_status = CampaignLifecycleStatus.ACTIVE
        game_session = GameSession(title=campaign.name, campaign=campaign)
        game_session.runtime = SessionRuntime(status=RuntimeStatus.IDLE)
        game_session.character_states = [
            SessionCharacterState(
                character=membership.character,
                current_hp=membership.character.max_hp,
                max_hp_snapshot=membership.character.max_hp,
            )
            for membership in campaign.memberships
        ]
        self.session.add(game_session)
        await self.session.flush()
        for membership in campaign.memberships:
            membership.joined_session_id = game_session.id
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def pause(self, campaign_id: str) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.lifecycle_status != CampaignLifecycleStatus.ACTIVE:
            raise ConflictError("CAMPAIGN_NOT_ACTIVE", "只有进行中的战役可以暂停。")
        runtime = next(
            (item.runtime for item in campaign.sessions if item.runtime is not None),
            None,
        )
        if runtime is not None:
            runtime.generation += 1
            runtime.active_agent_run_id = None
            if runtime.status != RuntimeStatus.WAITING_FOR_DM:
                runtime.status = RuntimeStatus.IDLE
        campaign.lifecycle_status = CampaignLifecycleStatus.PAUSED
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def resume(self, campaign_id: str) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.lifecycle_status != CampaignLifecycleStatus.PAUSED:
            raise ConflictError("CAMPAIGN_NOT_PAUSED", "只有已暂停的战役可以继续。")
        existing_active = await self.session.scalar(
            select(Campaign.id).where(Campaign.lifecycle_status == CampaignLifecycleStatus.ACTIVE)
        )
        if existing_active is not None:
            raise ConflictError("ACTIVE_CAMPAIGN_EXISTS", "当前已有一个正在进行的战役。")
        campaign.lifecycle_status = CampaignLifecycleStatus.ACTIVE
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def add_member(self, campaign_id: str, payload: CampaignMemberAdd) -> Campaign:
        campaign = await self.get(campaign_id)
        self._check_revision(campaign, payload.revision)
        if campaign.lifecycle_status != CampaignLifecycleStatus.ACTIVE:
            raise ConflictError("CAMPAIGN_NOT_ACTIVE", "只有进行中的战役可以中途加入角色。")
        if len(campaign.memberships) >= 6:
            raise AppError("INVALID_ROSTER_SIZE", "战役最多只能有 6 名角色。")
        if any(item.character_id == payload.character_id for item in campaign.memberships):
            raise ConflictError("CHARACTER_ALREADY_MEMBER", "该角色已经在战役阵容中。")
        character = await self.session.get(Character, payload.character_id)
        if character is None:
            raise AppError("CHARACTER_NOT_FOUND", "角色不存在。", status_code=404)
        if any(
            item.character.name.casefold() == character.name.casefold()
            for item in campaign.memberships
        ):
            raise ConflictError("DUPLICATE_CHARACTER_NAME", "同一战役中的角色名称不能重复。")
        active_session = next(
            (item for item in campaign.sessions if item.status == SessionStatus.ACTIVE),
            None,
        )
        membership = CampaignMembership(
            campaign=campaign,
            character=character,
            joined_session_id=active_session.id if active_session else None,
            joined_after_message_id=(
                await self.session.scalar(
                    select(Message.id)
                    .where(Message.session_id == active_session.id)
                    .order_by(Message.sequence_no.desc())
                    .limit(1)
                )
                if active_session is not None
                else None
            ),
        )
        self.session.add(membership)
        if active_session is not None:
            active_session.character_states.append(
                SessionCharacterState(
                    character=character,
                    current_hp=character.max_hp,
                    max_hp_snapshot=character.max_hp,
                )
            )
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def archive(self, campaign_id: str) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.lifecycle_status not in {
            CampaignLifecycleStatus.PREPARATION,
            CampaignLifecycleStatus.COMPLETED,
        }:
            raise ConflictError("CAMPAIGN_NOT_ARCHIVABLE", "只有筹备中或已完成的战役可以归档。")
        campaign.archived_at = datetime.now(UTC)
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def unarchive(self, campaign_id: str) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.archived_at is None:
            raise ConflictError("CAMPAIGN_NOT_ARCHIVED", "该战役当前没有归档。")
        campaign.archived_at = None
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def reset(self, campaign_id: str) -> Campaign:
        campaign = await self.get(campaign_id)
        for game_session in campaign.sessions:
            if game_session.runtime is not None:
                game_session.runtime.generation += 1
                game_session.runtime.active_agent_run_id = None
                game_session.runtime.status = RuntimeStatus.ENDED
        member_ids = [item.character_id for item in campaign.memberships]
        if member_ids:
            await self.session.execute(
                CharacterMemory.__table__.delete().where(
                    CharacterMemory.character_id.in_(member_ids),
                    CharacterMemory.source_campaign_id == campaign.id,
                )
            )
            profiles = list(
                await self.session.scalars(
                    select(CharacterProfile).where(CharacterProfile.character_id.in_(member_ids))
                )
            )
            for profile in profiles:
                profile.content = ""
                profile.status = ProfileStatus.NEEDS_REBUILD
                profile.revision += 1
        campaign.sessions.clear()
        campaign.lifecycle_status = CampaignLifecycleStatus.PREPARATION
        campaign.archived_at = None
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def complete(self, campaign_id: str) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.lifecycle_status not in {
            CampaignLifecycleStatus.ACTIVE,
            CampaignLifecycleStatus.PAUSED,
        }:
            raise ConflictError("CAMPAIGN_NOT_RUNNABLE", "只有进行中或已暂停的战役可以完成。")
        member_ids = [item.character_id for item in campaign.memberships]
        profiles = {
            profile.character_id: profile
            for profile in list(
                await self.session.scalars(
                    select(CharacterProfile).where(CharacterProfile.character_id.in_(member_ids))
                )
            )
        }
        memories = list(
            await self.session.scalars(
                select(CharacterMemory)
                .where(
                    CharacterMemory.character_id.in_(member_ids),
                    CharacterMemory.source_campaign_id == campaign.id,
                    CharacterMemory.origin == MemoryOrigin.AUTO,
                )
                .order_by(CharacterMemory.created_at)
            )
        )
        for character_id in member_ids:
            profile = profiles.get(character_id)
            items = [item.content for item in memories if item.character_id == character_id]
            if profile is not None and items:
                profile.content = (
                    f"{profile.content.rstrip()}\n\n"
                    f"【战役 {campaign.name} 的成长记录】\n- " + "\n- ".join(items)
                ).strip()
                profile.status = ProfileStatus.READY
                profile.updated_by = UpdatedBy.SYSTEM
                profile.revision += 1
        campaign.lifecycle_status = CampaignLifecycleStatus.COMPLETED
        for game_session in campaign.sessions:
            game_session.status = SessionStatus.ENDED
            game_session.ended_at = datetime.now(UTC)
            if game_session.runtime is not None:
                game_session.runtime.status = RuntimeStatus.ENDED
                game_session.runtime.generation += 1
                game_session.runtime.active_agent_run_id = None
        campaign.revision += 1
        await self.session.commit()
        game_session = next(iter(campaign.sessions), None)
        if game_session is not None:
            await SummaryService(self.session).build_for_campaign(game_session)
            await self.session.commit()
        return await self.get(campaign.id)

    async def reopen(self, campaign_id: str) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.lifecycle_status != CampaignLifecycleStatus.COMPLETED:
            raise ConflictError("CAMPAIGN_NOT_COMPLETED", "只有已完成的战役可以重新开启。")
        existing_active = await self.session.scalar(
            select(Campaign.id).where(Campaign.lifecycle_status == CampaignLifecycleStatus.ACTIVE)
        )
        if existing_active is not None:
            raise ConflictError("ACTIVE_CAMPAIGN_EXISTS", "当前已有一个正在进行的战役。")
        campaign.lifecycle_status = CampaignLifecycleStatus.ACTIVE
        campaign.archived_at = None
        for game_session in campaign.sessions:
            game_session.status = SessionStatus.ACTIVE
            game_session.ended_at = None
            if game_session.runtime is not None:
                game_session.runtime.status = RuntimeStatus.IDLE
        campaign.revision += 1
        await self.session.commit()
        return await self.get(campaign.id)

    async def delete(self, campaign_id: str) -> None:
        campaign = await self.get(campaign_id)
        if campaign.lifecycle_status in {
            CampaignLifecycleStatus.ACTIVE,
            CampaignLifecycleStatus.PAUSED,
        }:
            raise ConflictError(
                "ACTIVE_CAMPAIGN_DELETE_FORBIDDEN",
                "请先完成战役后再永久删除。",
            )
        await self.session.delete(campaign)
        await self.session.commit()

    async def create_session(self, campaign_id: str, payload: SessionCreate) -> GameSession:
        campaign = await self.get(campaign_id)
        if campaign.lifecycle_status != CampaignLifecycleStatus.ACTIVE:
            raise ConflictError("CAMPAIGN_NOT_ACTIVE", "只有进行中的战役可以创建 Session。")
        if any(game_session.status == SessionStatus.ACTIVE for game_session in campaign.sessions):
            raise ConflictError("ACTIVE_SESSION_EXISTS", "当前战役已有未结束的 Session。")

        previous_session = max(
            (item for item in campaign.sessions if item.status == SessionStatus.ENDED),
            key=lambda item: item.started_at,
            default=None,
        )
        previous_hp = (
            {state.character_id: state.current_hp for state in previous_session.character_states}
            if previous_session is not None
            else {}
        )
        game_session = GameSession(title=payload.title.strip(), campaign=campaign)
        game_session.runtime = SessionRuntime(status=RuntimeStatus.IDLE)
        game_session.character_states = [
            SessionCharacterState(
                character=membership.character,
                current_hp=min(
                    previous_hp.get(membership.character.id, membership.character.max_hp),
                    membership.character.max_hp,
                ),
                max_hp_snapshot=membership.character.max_hp,
            )
            for membership in campaign.memberships
        ]
        self.session.add(game_session)
        await self.session.commit()
        return game_session

    async def end_session(self, session_id: str) -> GameSession:
        game_session = await self.get_session(session_id)
        if game_session.status != SessionStatus.ACTIVE:
            raise ConflictError("SESSION_ALREADY_ENDED", "Session 已经结束。")
        game_session.status = SessionStatus.ENDED
        game_session.ended_at = datetime.now(UTC)
        game_session.runtime.status = RuntimeStatus.ENDED
        game_session.runtime.generation += 1
        game_session.runtime.active_agent_run_id = None
        await self.session.commit()
        await SummaryService(self.session).build_for_campaign(game_session)
        await self.session.commit()
        return game_session

    async def get_session(self, session_id: str) -> GameSession:
        game_session = await self.session.scalar(
            select(GameSession)
            .where(GameSession.id == session_id)
            .options(
                selectinload(GameSession.campaign),
                selectinload(GameSession.runtime),
                selectinload(GameSession.character_states).selectinload(
                    SessionCharacterState.character
                ),
            )
        )
        if game_session is None:
            raise NotFoundError("Session", session_id)
        return game_session

    async def get_campaign_runtime(self, campaign_id: str) -> GameSession:
        campaign = await self.get(campaign_id)
        game_session = campaign.sessions[0] if campaign.sessions else None
        if game_session is None:
            raise ConflictError(
                "CAMPAIGN_NOT_STARTED",
                "战役尚未启动，启动后才能进入连续跑团页面。",
            )
        return await self.get_session(game_session.id)

    async def update_campaign_hp(
        self, campaign_id: str, character_id: str, payload: HpUpdate
    ) -> GameSession:
        game_session = await self.get_campaign_runtime(campaign_id)
        return await self.update_hp(game_session.id, character_id, payload)

    async def update_hp(self, session_id: str, character_id: str, payload: HpUpdate) -> GameSession:
        game_session = await self.get_session(session_id)
        if game_session.campaign.lifecycle_status != CampaignLifecycleStatus.ACTIVE:
            raise ConflictError("CAMPAIGN_NOT_ACTIVE", "只有进行中的战役可以修改 HP。")
        state = next(
            (item for item in game_session.character_states if item.character_id == character_id),
            None,
        )
        if state is None:
            raise NotFoundError("SessionCharacterState", character_id)
        if payload.current_hp > state.max_hp_snapshot:
            raise AppError("HP_EXCEEDS_MAX", "当前 HP 不能超过最大 HP。")
        state.current_hp = payload.current_hp
        await self.session.commit()
        return game_session

    @staticmethod
    def _check_revision(campaign: Campaign, expected_revision: int) -> None:
        if campaign.revision != expected_revision:
            raise ConflictError(
                "CAMPAIGN_REVISION_CONFLICT",
                "战役已在其他页面发生变化，请刷新后重试。",
            )
