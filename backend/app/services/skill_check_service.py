from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.api.schemas.skill_checks import (
    SkillCheckAdjudicate,
    SkillCheckCreate,
    SkillCheckVoid,
)
from backend.app.core.errors import ConflictError, NotFoundError
from backend.app.db.models import (
    Campaign,
    CampaignMembership,
    Character,
    GameSession,
    SkillCheck,
)
from backend.app.domain.enums import (
    CampaignLifecycleStatus,
    RollMode,
    SkillCheckStatus,
    SkillCheckSystemOutcome,
)
from backend.app.services.skill_service import SkillService


class SkillCheckService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_campaign(self, campaign_id: str) -> Campaign:
        campaign = await self.session.scalar(
            select(Campaign)
            .where(Campaign.id == campaign_id)
            .options(
                selectinload(Campaign.memberships)
                .selectinload(CampaignMembership.character)
                .selectinload(Character.skill_set),
            )
        )
        if campaign is None:
            raise NotFoundError("Campaign", campaign_id)
        return campaign

    async def _get_runtime(self, campaign_id: str) -> GameSession:
        game_session = await self.session.scalar(
            select(GameSession)
            .where(GameSession.campaign_id == campaign_id)
            .options(selectinload(GameSession.campaign))
        )
        if game_session is None:
            raise ConflictError("CAMPAIGN_NOT_STARTED", "战役尚未启动。")
        if game_session.campaign.lifecycle_status != CampaignLifecycleStatus.ACTIVE:
            raise ConflictError("CAMPAIGN_NOT_ACTIVE", "只有进行中的战役可以投骰。")
        return game_session

    async def list_campaign_skills(
        self, campaign_id: str
    ) -> list[tuple[Character, dict[str, int]]]:
        campaign = await self._get_campaign(campaign_id)
        values: list[tuple[Character, dict[str, int]]] = []
        for membership in campaign.memberships:
            skill_set = membership.character.skill_set
            if skill_set is None:
                skill_set = await SkillService(self.session).get(membership.character_id)
            values.append((membership.character, skill_set.modifiers))
        return values

    async def list(self, campaign_id: str) -> list[SkillCheck]:
        await self._get_campaign(campaign_id)
        return list(
            await self.session.scalars(
                select(SkillCheck)
                .where(SkillCheck.campaign_id == campaign_id)
                .options(selectinload(SkillCheck.character))
                .order_by(SkillCheck.created_at.desc())
            )
        )

    async def create(self, campaign_id: str, payload: SkillCheckCreate) -> SkillCheck:
        existing = await self.session.scalar(
            select(SkillCheck).where(SkillCheck.client_request_id == str(payload.client_request_id))
        )
        if existing is not None:
            if existing.campaign_id != campaign_id:
                raise ConflictError(
                    "CLIENT_REQUEST_ID_REUSED", "这条客户端请求 ID 已用于其他战役。"
                )
            return await self._get(existing.id)

        game_session = await self._get_runtime(campaign_id)
        campaign = await self._get_campaign(campaign_id)
        membership = next(
            (item for item in campaign.memberships if item.character_id == payload.character_id),
            None,
        )
        if membership is None:
            raise ConflictError("CHARACTER_NOT_IN_CAMPAIGN", "检定角色必须是当前战役成员。")
        skill_set = membership.character.skill_set
        if skill_set is None:
            skill_set = await SkillService(self.session).get(payload.character_id)
        modifier = skill_set.modifiers.get(payload.skill.value)
        if modifier is None:
            raise ConflictError("SKILL_NOT_CONFIGURED", "该角色没有配置这项技能加值。")

        die_one = secrets.randbelow(20) + 1
        die_two = None
        selected_die = die_one
        if payload.roll_mode != RollMode.NORMAL:
            die_two = secrets.randbelow(20) + 1
            selected_die = (
                max(die_one, die_two)
                if payload.roll_mode == RollMode.ADVANTAGE
                else min(die_one, die_two)
            )
        total = selected_die + modifier
        system_outcome = SkillCheckSystemOutcome.UNRESOLVED
        if payload.dc is not None:
            system_outcome = (
                SkillCheckSystemOutcome.PASS
                if total >= payload.dc
                else SkillCheckSystemOutcome.FAIL
            )
        check = SkillCheck(
            campaign_id=campaign_id,
            session_id=game_session.id,
            character_id=payload.character_id,
            skill=payload.skill.value,
            modifier_snapshot=modifier,
            roll_mode=payload.roll_mode,
            die_one=die_one,
            die_two=die_two,
            selected_die=selected_die,
            total=total,
            dc=payload.dc,
            system_outcome=system_outcome,
            reason=payload.reason.strip() if payload.reason else None,
            client_request_id=str(payload.client_request_id),
            status=SkillCheckStatus.VALID,
        )
        self.session.add(check)
        await self.session.commit()
        return await self._get(check.id)

    async def adjudicate(self, check_id: str, payload: SkillCheckAdjudicate) -> SkillCheck:
        check = await self._get(check_id)
        if check.status != SkillCheckStatus.VALID:
            raise ConflictError("SKILL_CHECK_NOT_VALID", "作废的检定不能裁决。")
        if check.dc is not None or check.system_outcome != SkillCheckSystemOutcome.UNRESOLVED:
            raise ConflictError("SKILL_CHECK_ALREADY_RESOLVED", "有 DC 的检定已经由系统计算结果。")
        check.dm_adjudication = payload.outcome
        check.adjudicated_at = datetime.now(UTC)
        await self.session.commit()
        return await self._get(check.id)

    async def void(self, check_id: str, payload: SkillCheckVoid) -> SkillCheck:
        check = await self._get(check_id)
        if check.status != SkillCheckStatus.VALID:
            raise ConflictError("SKILL_CHECK_ALREADY_VOID", "该检定已经作废。")
        check.status = SkillCheckStatus.VOID
        check.void_reason = payload.reason.strip()
        await self.session.commit()
        return await self._get(check.id)

    async def _get(self, check_id: str) -> SkillCheck:
        check = await self.session.scalar(
            select(SkillCheck)
            .where(SkillCheck.id == check_id)
            .options(selectinload(SkillCheck.character))
        )
        if check is None:
            raise NotFoundError("SkillCheck", check_id)
        return check
