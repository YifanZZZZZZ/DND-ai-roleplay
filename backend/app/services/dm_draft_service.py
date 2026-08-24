# ruff: noqa: E501
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.agents.dm_agent import DeepSeekDmAgent, DmAgent, DmDecision
from backend.app.agents.dm_prompt import (
    RECENT_MESSAGE_LIMIT,
    DmContextInput,
    build_context,
    compose_system_prompt,
)
from backend.app.api.schemas.dm_drafts import DmDraftUpdate
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ConflictError, NotFoundError
from backend.app.db.models import (
    Campaign,
    CampaignDmDraft,
    CampaignNpc,
    GameSession,
    Message,
    MessageRecipient,
    SkillCheck,
)
from backend.app.domain.enums import (
    CampaignLifecycleStatus,
    CampaignPlayMode,
    DmDraftStatus,
    DmDraftTriggerType,
    MessageAudience,
    MessageSenderType,
)
from backend.app.services.acquaintance_service import AcquaintanceService
from backend.app.services.campaign_service import CampaignService


class DmDraftService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        agent: DmAgent | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.agent = agent

    async def _generate(self, system_prompt: str, context: str) -> DmDecision:
        agent = self.agent or DeepSeekDmAgent(self.settings)
        return (await agent.draft(system_prompt, context)).output

    async def _npc_cards(self, campaign_id: str) -> list[dict[str, str]]:
        rows = await self.session.scalars(
            select(CampaignNpc)
            .where(CampaignNpc.campaign_id == campaign_id)
            .order_by(CampaignNpc.name)
        )
        return [
            {
                "name": npc.name,
                "role": npc.role,
                "personality": npc.personality,
                "ideal": npc.ideal,
                "bond": npc.bond,
                "flaw": npc.flaw,
                "knows": npc.knows,
                "wants": npc.wants,
                "voice": npc.voice,
            }
            for npc in rows
        ]

    async def _recent_messages(
        self, session_id: str, limit: int = RECENT_MESSAGE_LIMIT
    ) -> list[tuple[str, str, str]]:
        """Sender name and audience included — the AI DM used to see neither."""
        from backend.app.services.message_projection import EffectiveMessageProjection

        messages = list(
            await self.session.scalars(
                EffectiveMessageProjection.for_session(session_id)
                .order_by(None)
                .order_by(Message.sequence_no.desc())
                .limit(limit)
                .options(selectinload(Message.recipients).selectinload(MessageRecipient.character))
            )
        )
        messages.reverse()
        rendered: list[tuple[str, str, str]] = []
        for message in messages:
            speaker = (
                message.sender_character.name
                if message.sender_character is not None
                else "DM"
            )
            if message.audience == MessageAudience.PUBLIC:
                audience = "公开"
            else:
                names = "、".join(
                    recipient.character.name for recipient in message.recipients
                )
                audience = f"私密→{names}" if names else "私密"
            rendered.append((speaker, audience, message.content))
        return rendered

    async def _build_context(
        self,
        campaign: Campaign,
        *,
        session_id: str | None,
        trigger_speaker: str | None = None,
        trigger_content: str | None = None,
        waiting_request: str | None = None,
        skill_check: str | None = None,
        dm_draft: str | None = None,
        assist_mode: str = "POLISH",
    ) -> tuple[str, str]:
        """Single entry point. Every trigger type gets the same world state."""
        acquaintance_pairs = await AcquaintanceService(self.session).list_for_campaign(
            campaign.id
        )
        data = DmContextInput(
            module=campaign.module_content or campaign.dm_guide,
            scene_notes=campaign.scene_notes,
            npcs=await self._npc_cards(campaign.id),
            party=[
                (item.character.id, item.character.name, item.character.narration_notes)
                for item in campaign.memberships
            ],
            acquaintance=[
                (character_a.name, character_b.name, acquaintance is not None)
                for character_a, character_b, acquaintance in acquaintance_pairs
            ],
            recent_messages=(
                await self._recent_messages(session_id) if session_id else []
            ),
            trigger_speaker=trigger_speaker,
            trigger_content=trigger_content,
            waiting_request=waiting_request,
            skill_check=skill_check,
            dm_draft=dm_draft,
            assist_mode=assist_mode,
        )
        system_prompt = compose_system_prompt(
            style_instructions=campaign.style_instructions,
            has_dm_draft=bool(dm_draft and dm_draft.strip()),
            assist_mode=assist_mode,
        )
        return system_prompt, build_context(data)

    async def get(self, draft_id: str) -> CampaignDmDraft:
        draft = await self.session.scalar(
            select(CampaignDmDraft).where(CampaignDmDraft.id == draft_id)
        )
        if draft is None:
            raise NotFoundError("Campaign DM Draft", draft_id)
        return draft

    async def list(self, campaign_id: str) -> list[CampaignDmDraft]:
        await CampaignService(self.session).get(campaign_id)
        result = await self.session.scalars(
            select(CampaignDmDraft)
            .where(CampaignDmDraft.campaign_id == campaign_id)
            .order_by(CampaignDmDraft.created_at.desc())
        )
        return list(result)

    async def create(
        self,
        campaign_id: str,
        prompt: str,
        source_skill_check_id: str | None,
        assist_mode: str = "POLISH",
    ) -> CampaignDmDraft:
        campaign = await CampaignService(self.session).get(campaign_id)
        if campaign.lifecycle_status != CampaignLifecycleStatus.ACTIVE:
            raise ConflictError(
                "CAMPAIGN_NOT_ACTIVE", "只有进行中的 Campaign 可以生成 AI DM 草稿。"
            )
        runtime = await CampaignService(self.session).get_campaign_runtime(campaign_id)
        check_context = None
        if source_skill_check_id:
            check = await self.session.scalar(
                select(SkillCheck).where(
                    SkillCheck.id == source_skill_check_id, SkillCheck.campaign_id == campaign_id
                )
            )
            if check is None:
                raise NotFoundError("Skill Check", source_skill_check_id)
            check_context = (
                f"{check.skill}：投出 {check.total}，"
                f"系统结论 {check.system_outcome}，DM 裁决 {check.dm_adjudication or '未裁决'}。"
            )
        trigger = None
        if runtime.runtime.waiting_message_id is not None:
            trigger = await self.session.scalar(
                select(Message)
                .where(Message.id == runtime.runtime.waiting_message_id)
                .options(selectinload(Message.sender_character))
            )
        system_prompt, context = await self._build_context(
            campaign,
            session_id=runtime.id,
            trigger_speaker=(
                trigger.sender_character.name
                if trigger is not None and trigger.sender_character is not None
                else None
            ),
            trigger_content=trigger.content if trigger is not None else None,
            waiting_request=runtime.runtime.waiting_request,
            skill_check=check_context,
            dm_draft=prompt,
            assist_mode=assist_mode,
        )
        result = await self._generate(system_prompt, context)
        audience, recipient_ids = self._normalize_visibility(campaign, result)
        draft = CampaignDmDraft(
            campaign_id=campaign_id,
            session_id=runtime.id,
            source_skill_check_id=source_skill_check_id,
            trigger_type=DmDraftTriggerType.MANUAL_ASSIST,
            prompt=prompt,
            content=result.content,
            audience=audience,
            recipient_character_ids=recipient_ids,
            improvised_notes=list(result.improvised_notes),
            status=DmDraftStatus.READY,
        )
        self.session.add(draft)
        await self.session.commit()
        return draft

    async def generate_for_character_reply(self, message_id: str) -> CampaignDmDraft | None:
        message = await self.session.scalar(
            select(Message)
            .where(Message.id == message_id)
            .options(selectinload(Message.sender_character))
        )
        if message is None or message.sender_type != MessageSenderType.CHARACTER:
            return None
        runtime = await self.session.scalar(
            select(GameSession)
            .where(GameSession.id == message.session_id)
            .options(selectinload(GameSession.runtime))
        )
        if runtime is None:
            return None
        campaign = await self.session.get(Campaign, runtime.campaign_id)
        if campaign is None or campaign.play_mode != CampaignPlayMode.NARRATIVE:
            return None
        existing_drafts = list(
            await self.session.scalars(
                select(CampaignDmDraft).where(
                    CampaignDmDraft.campaign_id == campaign.id,
                    CampaignDmDraft.trigger_type != DmDraftTriggerType.OPENING,
                    CampaignDmDraft.status.in_(
                        [DmDraftStatus.GENERATING, DmDraftStatus.READY, DmDraftStatus.DRAFT]
                    ),
                )
            )
        )
        for existing in existing_drafts:
            if existing.source_message_id != message.id:
                existing.status = DmDraftStatus.STALE
        same_message = next(
            (
                item
                for item in existing_drafts
                if item.trigger_type == DmDraftTriggerType.CHARACTER_REPLY
                and item.source_message_id == message.id
            ),
            None,
        )
        if same_message is not None:
            await self.session.commit()
            return same_message
        draft = CampaignDmDraft(
            campaign_id=campaign.id,
            session_id=runtime.id,
            source_message_id=message.id,
            trigger_type=DmDraftTriggerType.CHARACTER_REPLY,
            content="",
            status=DmDraftStatus.GENERATING,
        )
        self.session.add(draft)
        await self.session.commit()
        if not self.settings.dm_agent_is_configured and self.agent is None:
            draft.status = DmDraftStatus.FAILED
            draft.content = "AI DM 尚未配置，无法生成自动草稿。"
            await self.session.commit()
            return draft
        try:
            system_prompt, context = await self._build_context(
                campaign,
                session_id=runtime.id,
                trigger_speaker=(
                    message.sender_character.name
                    if message.sender_character is not None
                    else None
                ),
                trigger_content=message.content,
                waiting_request=runtime.runtime.waiting_request,
            )
            result = await self._generate(system_prompt, context)
        except Exception:
            await self.session.refresh(draft)
            if draft.status == DmDraftStatus.GENERATING:
                draft.status = DmDraftStatus.FAILED
                draft.content = "AI DM 草稿生成失败，请重试或使用手动 DM。"
            await self.session.commit()
            raise
        await self.session.refresh(draft)
        if draft.status == DmDraftStatus.STALE:
            return draft
        audience, recipient_ids = self._normalize_visibility(campaign, result)
        draft.content = result.content
        draft.audience = audience
        draft.recipient_character_ids = recipient_ids
        draft.improvised_notes = list(result.improvised_notes)
        draft.status = DmDraftStatus.READY
        await self.session.commit()
        return draft

    async def generate_opening(self, campaign_id: str) -> CampaignDmDraft:
        campaign = await CampaignService(self.session).get(campaign_id)
        if campaign.lifecycle_status != CampaignLifecycleStatus.PREPARATION:
            raise ConflictError("CAMPAIGN_NOT_PREPARATION", "只有筹备中的 Campaign 可以生成开场草稿。")
        if not (campaign.module_content or campaign.dm_guide).strip():
            raise ConflictError("MODULE_CONTENT_REQUIRED", "生成开场草稿前必须提供模组内容。")
        existing = await self.session.scalar(
            select(CampaignDmDraft).where(
                CampaignDmDraft.campaign_id == campaign_id,
                CampaignDmDraft.trigger_type == DmDraftTriggerType.OPENING,
                CampaignDmDraft.status.in_([DmDraftStatus.GENERATING, DmDraftStatus.READY]),
            )
        )
        if existing is not None:
            return existing
        draft = CampaignDmDraft(
            campaign_id=campaign_id,
            trigger_type=DmDraftTriggerType.OPENING,
            content="",
            status=DmDraftStatus.GENERATING,
        )
        self.session.add(draft)
        await self.session.commit()
        if not self.settings.dm_agent_is_configured and self.agent is None:
            draft.status = DmDraftStatus.FAILED
            draft.content = "AI DM 尚未配置，无法生成开场草稿。"
            await self.session.commit()
            return draft
        system_prompt, context = await self._build_context(
            campaign,
            session_id=None,
            dm_draft=campaign.opening_instructions or None,
            assist_mode="EXPAND",
        )
        try:
            result = await self._generate(system_prompt, context)
        except Exception:
            draft.status = DmDraftStatus.FAILED
            draft.content = "AI DM 开场草稿生成失败，请重试。"
            await self.session.commit()
            raise
        draft.content = result.content
        draft.audience = MessageAudience.PUBLIC
        draft.recipient_character_ids = []
        draft.improvised_notes = list(result.improvised_notes)
        draft.status = DmDraftStatus.READY
        await self.session.commit()
        return draft

    async def update(self, draft_id: str, payload: DmDraftUpdate) -> CampaignDmDraft:
        draft = await self.get(draft_id)
        if draft.status not in {DmDraftStatus.DRAFT, DmDraftStatus.READY}:
            raise ConflictError("DM_DRAFT_NOT_EDITABLE", "只有草稿状态的 AI DM 内容可以编辑。")
        if draft.revision != payload.revision:
            raise ConflictError("REVISION_CONFLICT", "草稿已被更新，请刷新后重试。")
        draft.content = payload.content.strip()
        campaign = await CampaignService(self.session).get(draft.campaign_id)
        audience, recipient_ids = self._validate_requested_visibility(
            campaign, MessageAudience(payload.audience), payload.recipient_character_ids
        )
        draft.audience = audience
        draft.recipient_character_ids = recipient_ids
        draft.revision += 1
        await self.session.commit()
        return draft

    def _normalize_visibility(
        self, campaign: Campaign, result: DmDecision
    ) -> tuple[MessageAudience, list[str]]:
        """A PRIVATE draft never silently becomes PUBLIC.

        Downgrading on a hallucinated ID turned a secret meant for one character
        into a party-wide announcement, with nothing in the UI to show it had
        happened. Unknown IDs are dropped instead; if none survive, the draft
        stays PRIVATE with an empty recipient list so the DM has to choose.
        """
        member_ids = {membership.character_id for membership in campaign.memberships}
        recipient_ids = [
            character_id
            for character_id in dict.fromkeys(result.recipient_character_ids)
            if character_id in member_ids
        ]
        if result.audience == "PRIVATE":
            return MessageAudience.PRIVATE, recipient_ids
        return MessageAudience.PUBLIC, []

    def _validate_requested_visibility(
        self,
        campaign: Campaign,
        audience: MessageAudience,
        recipient_ids: list[str],
    ) -> tuple[MessageAudience, list[str]]:
        unique_ids = list(dict.fromkeys(recipient_ids))
        if audience == MessageAudience.PUBLIC:
            return MessageAudience.PUBLIC, []
        if not unique_ids:
            raise ConflictError("PRIVATE_RECIPIENT_REQUIRED", "私密 DM 草稿至少需要一个收件角色。")
        if audience != MessageAudience.PRIVATE:
            raise ConflictError("INVALID_DRAFT_AUDIENCE", "DM 草稿只能公开或私密发送。")
        member_ids = {membership.character_id for membership in campaign.memberships}
        if not set(unique_ids).issubset(member_ids):
            raise ConflictError(
                "PRIVATE_RECIPIENT_NOT_CAMPAIGN_MEMBER",
                "私密 DM 草稿的收件人必须是当前战役角色。",
            )
        return MessageAudience.PRIVATE, unique_ids

    async def mark_published(self, draft_id: str, session_id: str | None = None) -> CampaignDmDraft:
        draft = await self.get(draft_id)
        if draft.status not in {DmDraftStatus.DRAFT, DmDraftStatus.READY}:
            raise ConflictError("DM_DRAFT_NOT_PUBLISHABLE", "草稿已经发布或丢弃。")
        draft.status = DmDraftStatus.SENT
        if session_id is not None:
            draft.session_id = session_id
        await self.session.commit()
        return draft

    async def discard(self, draft_id: str) -> CampaignDmDraft:
        draft = await self.get(draft_id)
        if draft.status not in {DmDraftStatus.DRAFT, DmDraftStatus.READY}:
            raise ConflictError("DM_DRAFT_NOT_DISCARDABLE", "只有待确认草稿可以丢弃。")
        draft.status = DmDraftStatus.DISCARDED
        draft.revision += 1
        await self.session.commit()
        return draft
